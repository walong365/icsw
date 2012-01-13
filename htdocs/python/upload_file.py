#!/usr/bin/python -Ot
#
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
""" upload file script """

import logging_tools

def process_page(req):
    needed_keys = ["target_dir"]
    missing_keys = [key for key in needed_keys if key not in req.sys_args.keys()]
    if missing_keys:
        req.write("%s missing: %s" % (logging_tools.get_plural("key", len(missing_keys)),
                                      ", ".join(missing_keys)))
    else:
        if not req.my_files:
            req.write("No upload files specified")
        else:
            req.write("OK %s" % (str(req.my_files.keys())))
            
