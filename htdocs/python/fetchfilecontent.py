#!/usr/bin/python -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2001,2002,2003,2004,2005,2007 Andreas Lang-Nevyjel, init.at
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
""" fetches file content """

import tools

def process_page(req):
    req.content_type = "text/plain; name=\"syslog\""
    server_name = req.sys_args.get("server", "")
    file_name = req.sys_args.get("file", "")
    if not server_name or not file_name:
        req.write("Server or file_name not specified")
    else:
        ds_command = tools.s_command(req, "server", 8004, "get_file_content", [], 10, server_name, add_dict={"file_names" : [file_name]})
        tools.iterate_s_commands([ds_command])
        if ds_command.server_reply:
            if ds_command.get_state() == "o":
                file_content_dict = ds_command.server_reply.get_option_dict()
                if file_content_dict.has_key(file_name) and file_content_dict[file_name].has_key("content"):
                    req.write(file_content_dict[file_name]["content"])
                else:
                    req.write("Error not content information for file %s" % (file_name))
            else:
                req.write("Error connecting to server %s" % (server_name))
        else:
            req.write("Got no valid server_reply")
