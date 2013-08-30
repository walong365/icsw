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
import codecs
import grp
import logging_tools
import os
import process_tools
import pwd
import server_command
import shutil
import stat
import sys
from lxml.builder import E

class get_file_content(cs_base_class.server_com):
    def _call(self, cur_inst):
        for file_entry in cur_inst.srv_com.xpath(None, ".//ns:file"):
            try:
                if "encoding" in file_entry.attrib:
                    content = codecs.open(file_entry.attrib["name"], "r", file_entry.attrib["encoding"]).read()
                else:
                    content = open(file_entry.attrib["name"], "r").read()
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

class set_file_content(cs_base_class.server_com):
    def _call(self, cur_inst):
        for file_entry in cur_inst.srv_com.xpath(None, ".//ns:file"):
            try:
                if "encoding" in file_entry.attrib:
                    content = codecs.open(file_entry.attrib["name"], "w", file_entry.attrib["encoding"]).write(file_entry.text)
                else:
                    content = open(file_entry.attrib["name"], "r").write(file_entry.text)
            except:
                file_entry.attrib["error"] = "1"
                file_entry.attrib["error_str"] = process_tools.get_except_info()
            else:
                file_entry.attrib["error"] = "0"
            if not int(file_entry.get("error", "0")):
                _set_attributes(file_entry, cur_inst)
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "stored file contents",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)
        })

class get_dir_tree(cs_base_class.server_com):
    def _call(self, cur_inst):
        for top_el in cur_inst.srv_com.xpath(None, ".//ns:start_dir"):
            top_el.append(E.directory(full_path=top_el.text, start_dir="1"))
            for cur_dir, dir_list, file_list in os.walk(top_el.text):
                add_el = top_el.find(".//directory[@full_path='%s']" % (cur_dir))
                for new_dir in sorted(dir_list):
                    add_el.append(
                        E.directory(
                            full_path=os.path.join(add_el.attrib["full_path"], new_dir),
                            path=new_dir
                        )
                    )
                for new_file in sorted(file_list):
                    add_el.append(
                        E.file(
                            name=new_file,
                            size="%d" % (os.stat(os.path.join(cur_dir, new_file))[stat.ST_SIZE]),
                            ))
            for cur_idx, cur_el in enumerate(top_el.findall(".//*")):
                cur_el.attrib["idx"] = "%d" % (cur_idx)
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "read file contents",
            "state" : "%d" % (server_command.SRV_REPLY_STATE_OK)
        })

def _set_attributes(xml_el, cur_inst):
    try:
        if "user" in xml_el.attrib or "group" in xml_el.attrib:
            el_user = xml_el.get("user", "root")
            el_group = xml_el.get("group", "root")
            process_tools.change_user_group_path(xml_el.text, el_user, el_group, log_com=cur_inst.log)
        if "mode" in xml_el.attrib:
            os.chmod(xml_el.text, int(xml_el.get("mode"), 8))
    except:
        xml_el.attrib["error"] = "1"
        xml_el.attrib["error_str"] = process_tools.get_except_info()

class create_dir(cs_base_class.server_com):
    def _call(self, cur_inst):
        created, failed = (0, 0)
        for dir_entry in cur_inst.srv_com.xpath(None, ".//ns:dir"):
            if not os.path.isdir(dir_entry.text):
                try:
                    os.makedirs(dir_entry.text)
                except:
                    dir_entry.attrib["error"] = "1"
                    dir_entry.attrib["error_str"] = process_tools.get_except_info()
                    failed += 1
                else:
                    dir_entry.attrib["error"] = "0"
                    created += 1
            else:
                dir_entry.attrib["error"] = "0"
            if not int(dir_entry.get("error", "0")):
                _set_attributes(dir_entry, cur_inst)
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "created %s%s" % (
                logging_tools.get_plural("directory", created),
                " (%d failed)" % (failed) if failed else "",
                ),
            "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR if failed else server_command.SRV_REPLY_STATE_OK)
        })

class remove_dir(cs_base_class.server_com):
    def _call(self, cur_inst):
        created, failed = (0, 0)
        for dir_entry in cur_inst.srv_com.xpath(None, ".//ns:dir"):
            if os.path.isdir(dir_entry.text):
                try:
                    if int(dir_entry.get("recursive", "0")):
                        shutil.rmtree(dir_entry.text)
                    else:
                        os.rmdir(dir_entry.text)
                except:
                    dir_entry.attrib["error"] = "1"
                    dir_entry.attrib["error_str"] = process_tools.get_except_info()
                    failed += 1
                else:
                    dir_entry.attrib["error"] = "0"
                    created += 1
            else:
                dir_entry.attrib["error"] = "0"
        cur_inst.srv_com["result"].attrib.update({
            "reply" : "removed %s%s" % (
                logging_tools.get_plural("directory", created),
                " (%d failed)" % (failed) if failed else "",
                ),
            "state" : "%d" % (server_command.SRV_REPLY_STATE_ERROR if failed else server_command.SRV_REPLY_STATE_OK)
        })

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

