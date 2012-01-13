#!/usr/bin/python-init -Ot
# -*- coding: iso-8859-1 -*-
#
# Copyright (C) 2007 Andreas Lang, init.at
#
# Send feedback to: <lang@init.at>
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
""" wrapper to contact rrd-servers """

import gzip
import os
import os.path
import server_command
import net_tools

EXT_NB_HOSTS = "/etc/ext_netbotz_hosts"
NB_PICTURE_FILE = "/tmp/.nbdrop_picture"
NB_POST = ".nbdrop_post_"

def main():
    dst_servers = ["localhost"]
    if os.path.isfile(EXT_NB_HOSTS):
        dst_servers.extend([x.strip() for x in file(EXT_NB_HOSTS, "r").read().split("\n") if x.strip()])
    args, files = ({}, {})
    if os.path.isfile(NB_PICTURE_FILE):
        files = {"NETBOTZ_FILE" : (NB_PICTURE_FILE, file(NB_PICTURE_FILE, "r").read())}
        try:
            os.unlink(NB_PICTURE_FILE)
        except:
            pass
    for file_name in os.listdir("/tmp"):
        if file_name.startswith(NB_POST):
            full_file_name = "/tmp/%s" % (file_name)
            args[file_name[len(NB_POST) : ]] = file(full_file_name, "r").read().strip()
            try:
                os.unlink(full_file_name)
            except:
                pass
    for dst_server in dst_servers:
        print net_tools.single_connection(host=dst_server, port=8003, command=server_command.server_command(command="netbotz_drop",
                                                                                                      option_dict={"args"  : args,
                                                                                                                   "files" : files})).iterate()

if __name__ == "__main__":
    main()
    
