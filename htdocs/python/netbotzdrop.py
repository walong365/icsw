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
""" utility script for netbotz picture drop """

import os
import os.path
import tools
import html_tools
import process_tools
import xml_tools

EXT_NB_HOSTS = "/etc/ext_netbotz_hosts"

DEBUG_FILE = "/tmp/webfrontend.dbg"

def process_page(req):
    req.content_type = "text/plain"
    req.send_http_header()
    dst_servers = ["localhost"]
    if os.path.isfile(EXT_NB_HOSTS):
        dst_servers.extend([x.strip() for x in file(EXT_NB_HOSTS, "r").read().split("\n") if x.strip()])
    # fake config
    file(DEBUG_FILE, "w").write(str(dst_servers) + "\n")
    req.conf = {"server" : {"netbotz" : dict([(srv, srv) for srv in dst_servers])}}
    file(DEBUG_FILE, "w").write(str(req.conf) + "\n")
    req.info_stack = html_tools.message_log()
    try:
        com_list = [tools.s_command(req,
                                    "netbotz",
                                    8003,
                                    "netbotz_drop",
                                    [],
                                    timeout=10,
                                    hostname=h_name,
                                    add_dict={"args"  : req.sys_args,
                                              "files" : req.my_files}) for h_name in dst_servers]
        tools.iterate_s_commands(com_list)
    except:
        file(DEBUG_FILE, "w").write(str(process_tools.get_except_info()) + "\n")

