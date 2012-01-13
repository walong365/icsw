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
""" fech script """

def process_page(req):
    req.content_type = "text/plain"
    req.headers_out["Content-Disposition"] = "filename=\"script\""
    req.send_http_header()
    script_idx = req.sys_args.get("script", None)
    if script_idx:
        if script_idx.isdigit():
            req.dc.execute("SELECT cs.value,cs.name FROM config_script cs WHERE cs.config_script_idx=%d" % (int(script_idx)))
            if req.dc.rowcount:
                req.write(req.dc.fetchone()["value"])
            else:
                req.write("No script with script_idx '%s' found" % (script_idx))
        else:
            req.write("script_idx '%s' is not an integer" % (script_idx))
    else:
        req.write("script_idx not specified")
