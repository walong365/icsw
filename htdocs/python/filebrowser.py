#!/usr/bin/python -Otv
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2007,2008 Andreas Lang-Nevyjel, init.at
#
# Send feedback to: <lang-nevyjel@init.at>
# 
# This file belongs to webfrontend
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
""" filebrowser object definition """

import html_tools
import tools
import os
import os.path
import stat
import logging_tools
import difflib

class fb_object(object):
    def __init__(self, req, action_log, **args):
        self.__req = req
        self.__action_log = action_log
        self.__path = args["path"]
        self.__title = args.get("title", "Browsing under %s" % (self.__path))
        self.__contact_server = args.get("server", None)
        self.__href_prefix = args.get("href_prefix", "")
        self._check_rel_path()
        self.__add_command = self.__req.sys_args.get("add_command", "")
        self.any_changes_made = False
    def _check_rel_path(self):
        rel_path = self.__req.sys_args.get("rel_path", ".")
        abs_path = os.path.normpath("%s/%s" % (self.__path, rel_path))
        if abs_path.startswith(self.__path):
            pass
        else:
            rel_path, abs_path = (".", self.__path)
        self.__abs_path, self.__rel_path = (abs_path, rel_path)
    def process(self):
        ds_command = tools.s_command(self.__req, "cransys_server", 8004, "get_dir_content", [], 10, self.__contact_server, add_dict={"dir_names" : [self.__abs_path]})
        tools.iterate_s_commands([ds_command], self.__action_log)
        if ds_command.get_state() == "o":
            srv_reply = ds_command.server_reply.get_option_dict()
            left_table = self._show_reply(srv_reply)
            self.__req.write(left_table(""))
            if self.__add_command:
                self._handle_add_command()
    def _show_reply(self, srv_reply):
        srv_reply = srv_reply.values()[0]
        self.__req.write(html_tools.gen_hline(self.__title, 2))
        fb_table = html_tools.html_table(cls="normalsmall")
        fb_table[0]["class"] = "white"
        fb_table[None][0:3] = html_tools.content(self.__rel_path and "Relative directory is '%s'" % (self.__rel_path) or "showing top level directory", cls="left", type="th")
        dir_keys = srv_reply["entries"]["dirs"].keys()
        dir_keys.sort()
        line_idx = 0
        if self.__path != self.__abs_path:
            dir_keys.insert(0, "..")
        for act_dir_name in dir_keys:
            line_idx = 1 - line_idx
            fb_table[0]["class"] = "line1%d" % (line_idx)
            fb_table[None][0] = html_tools.content("dir", cls="center")
            if act_dir_name == "..":
                fb_table[None][0] = html_tools.content("<a href=\"%s&rel_path=%s\">..</a>" % (self.__href_prefix,
                                                                                              os.path.split(self.__abs_path)[0][len(self.__path):]))
                fb_table[None][0] = html_tools.content("one level up")
            else:
                act_dir = srv_reply["entries"]["dirs"][act_dir_name]
                fb_table[None][0] = html_tools.content("<a href=\"%s&rel_path=%s/%s\">%s</a>" % (self.__href_prefix,
                                                                                                 self.__rel_path,
                                                                                                 act_dir_name,
                                                                                                 act_dir_name), cls="left")
                fb_table[None][0] = html_tools.content("change to subdir %s" % (act_dir_name))
        file_keys = srv_reply["entries"]["files"].keys()
        file_keys.sort()
        for act_file_name in file_keys:
            line_idx = 1 - line_idx
            fb_table[0]["class"] = "line1%d" % (line_idx)
            file_type, act_file = srv_reply["entries"]["files"][act_file_name]
            fb_table[None][0] = html_tools.content(file_type == "F" and "file" or "link", cls="center")
            if file_type == "F":
                fb_table[None][0] = html_tools.content("<a href=\"%s&rel_path=%s&add_command=show&show_file=%s\">%s</a>" % (self.__href_prefix,
                                                                                                                            self.__rel_path,
                                                                                                                            act_file_name,
                                                                                                                            act_file_name), cls="left")
                fb_table[None][0] = html_tools.content(logging_tools.get_size_str(act_file[stat.ST_SIZE], long_version=True), cls="right")
            else:
                fb_table[None][0:2] = html_tools.content(act_file_name, cls="left")
        return fb_table
    def _handle_add_command(self):
        add_command = self.__add_command
        if add_command == "show" and self.__req.sys_args.get("show_file", ""):
            self._show_file(self.__req.sys_args["show_file"])
    def _show_file(self, file_name):
        ds_command = tools.s_command(self.__req, "cransys_server", 8004, "get_file_content", [], 10, self.__contact_server, add_dict={"file_names" : ["%s/%s" % (self.__abs_path, file_name)]})
        tools.iterate_s_commands([ds_command], self.__action_log)
        if ds_command.get_state() == "o":
            srv_reply = ds_command.server_reply.get_option_dict()
            self._show_file_content(srv_reply)
    def _show_file_content(self, srv_reply):
        saved = self.__req.sys_args.get("save_button", False)
        file_name = os.path.basename(srv_reply.keys()[0])
        file_content = srv_reply.values()[0]["content"]
        file_stat = srv_reply.values()[0]["stat"]
        file_lines = file_content.split("\n")
        num_lines = len(file_lines)
        longest_line = max([len(line) for line in file_lines])
        self.__req.write(html_tools.gen_hline("File %s has %s, longest line has %s" % (file_name,
                                                                                       logging_tools.get_plural("line", num_lines),
                                                                                       logging_tools.get_plural("character", longest_line)), 2))
        edit_area = html_tools.text_area(self.__req, "fedit", max_col_size=200, max_row_size=60, min_row_size=20, min_col_size=50)
        if saved:
            new_content = edit_area.check_selection("", file_content).replace("\r\n", "\n").replace("\r", "\n")
            pre_lines  = [x.rstrip() for x in file_lines]
            post_lines = [x.rstrip() for x in new_content.split("\n")]
            if pre_lines != post_lines:
                dif = difflib.Differ()
                diff_list = list(dif.compare(pre_lines, post_lines))
                self.__action_log.add_ok("Changelog for script", "log")
                for line in diff_list:
                    if line.startswith(" "):
                        self.__action_log.add_ok("    %s" % (line), "same")
                    else:
                        self.__action_log.add_warn("%s" % (line), "diff %s" % (line[0]))
                ds_command = tools.s_command(self.__req, "cransys_server", 8004, "put_file_content", [], 10, self.__contact_server, add_dict={"file_dict" : {"%s/%s" % (self.__abs_path, file_name) : {"content" : "\n".join(post_lines),
                                                                                                                                                                                                       "uid"     : file_stat[stat.ST_UID],
                                                                                                                                                                                                       "gid"     : file_stat[stat.ST_GID],
                                                                                                                                                                                                       "mode"    : file_stat[stat.ST_MODE]}}})
                tools.iterate_s_commands([ds_command], self.__action_log)
                self.any_changes_made = True
        else:
            edit_area[""] = file_content
        submit_button = html_tools.submit_button(self.__req, "save")
        self.__req.write("<form action=\"%s&rel_path=%s&add_command=show&show_file=%s&save_button=1\" method=post><div class=\"center\">%s</div><div class=\"center\">%s</div>" % (self.__href_prefix,
                                                                                                                                                                                   self.__rel_path,
                                                                                                                                                                                   file_name,
                                                                                                                                                                                   submit_button(""),
                                                                                                                                                                                   edit_area("")))
        self.__req.write("<div class=\"center\">%s</div></form>" % (submit_button("")))
